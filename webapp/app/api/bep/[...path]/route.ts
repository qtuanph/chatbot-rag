import { getToken } from "next-auth/jwt";
import { redirect } from "next/navigation";
import type { NextRequest } from "next/server";

const API_INTERNAL = process.env.API_INTERNAL_URL!;

// MIGRATED: Removed export const runtime = "nodejs" (default, not needed)
// MIGRATED: Removed export const dynamic = "force-dynamic" (dynamic is default with Cache Components)

async function proxyHandler(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const token = await getToken({
    req: request,
    secret: process.env.NEXTAUTH_SECRET,
  });

  const backendUrl = `${API_INTERNAL}/${path.join("/")}${request.nextUrl.search}`;

  // Build forwarding headers
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  if (token?.accessToken) {
    headers.set("Authorization", `Bearer ${token.accessToken}`);
  }
  const realIp = request.headers.get("x-real-ip");
  if (realIp) headers.set("X-Real-IP", realIp);
  const forwardedFor = request.headers.get("x-forwarded-for");
  if (forwardedFor) headers.set("X-Forwarded-For", forwardedFor);

  // Build fetch options
  const init = {
    method: request.method,
    headers,
    duplex: "half",
  } as RequestInit & { duplex: string };

  // Detect SSE or Upload requests to adjust timeout
  const isSSERequest = path.some((segment) => segment === "stream");
  const isUploadRequest = path.some((segment) => segment === "upload");

  let controller: AbortController | null = null;
  let timeoutId: ReturnType<typeof setTimeout> | null = null;
  
  if (!isSSERequest) {
    controller = new AbortController();
    init.signal = controller.signal;
    
    // 1 hour timeout for uploads, 30s for others
    const timeoutMs = isUploadRequest ? 3600_000 : 30_000;
    timeoutId = setTimeout(() => controller?.abort(), timeoutMs);
  }

  // Forward body for non-GET/HEAD requests
  let retryBody: Blob | null = null;
  if (request.method !== "GET" && request.method !== "HEAD") {
    if (isSSERequest || isUploadRequest) {
      // For SSE and uploads, pass body stream directly to avoid blocking
      init.body = request.body;
    } else {
      // Clone body for small requests to allow retry
      retryBody = await request.blob();
      init.body = retryBody;
    }
  }

  let backendRes: Response;
  try {
    backendRes = await fetch(backendUrl, init);
    if (timeoutId) clearTimeout(timeoutId);
  } catch (err: unknown) {
    // Retry once on socket close (worker restart / transient error)
    const isSocketError =
      err instanceof TypeError ||
      (err instanceof Error && /socket|closed|econnrefused|econnreset/i.test(err.message));

    if (isSocketError) {
      let retryTimeout: ReturnType<typeof setTimeout> | null = null;
      try {
        // New AbortController for retry — previous signal is already aborted
        const retryController = new AbortController();
        retryTimeout = setTimeout(() => retryController.abort(), 30_000);
        const retryInit = { ...init, signal: retryController.signal };
        if (retryBody) {
          retryInit.body = retryBody.slice(0, retryBody.size);
        }
        backendRes = await fetch(backendUrl, retryInit);
      } catch (retryErr: unknown) {
        const retryMsg = retryErr instanceof Error ? retryErr.message : "unknown";
        return new Response(
          JSON.stringify({ detail: `Backend service unavailable: ${retryMsg}` }),
          { status: 502, headers: { "content-type": "application/json" } },
        );
      } finally {
        if (retryTimeout) clearTimeout(retryTimeout);
      }
    } else {
      const errMsg = err instanceof Error ? err.message : "unknown error";
      // Identify if it was a timeout
      const isTimeout = err instanceof Error && (err.name === "AbortError" || /timeout/i.test(err.message));
      
      return new Response(
        JSON.stringify({ detail: isTimeout ? `Backend request timed out (limit: ${isUploadRequest ? "1h" : "30s"})` : `Backend request failed: ${errMsg}` }),
        { status: isTimeout ? 504 : 502, headers: { "content-type": "application/json" } },
      );
    }
  }

  // Build response headers
  const responseHeaders = new Headers();
  const resContentType = backendRes.headers.get("content-type");
  if (resContentType) responseHeaders.set("content-type", resContentType);

  // Redirect to login on 401 (token expired or invalid)
  if (backendRes.status === 401) {
    redirect("/login");
  }

  // SSE-specific headers to prevent buffering at every layer
  if (resContentType?.includes("text/event-stream")) {
    responseHeaders.set("Cache-Control", "no-cache, no-transform");
    responseHeaders.set("Connection", "keep-alive");
    responseHeaders.set("X-Accel-Buffering", "no");
  }

  return new Response(backendRes.body, {
    status: backendRes.status,
    statusText: backendRes.statusText,
    headers: responseHeaders,
  });
}

export async function GET(
  request: NextRequest,
  ctx: { params: Promise<{ path: string[] }> }
) {
  return proxyHandler(request, ctx);
}

export async function POST(
  request: NextRequest,
  ctx: { params: Promise<{ path: string[] }> }
) {
  return proxyHandler(request, ctx);
}

export async function PUT(
  request: NextRequest,
  ctx: { params: Promise<{ path: string[] }> }
) {
  return proxyHandler(request, ctx);
}

export async function PATCH(
  request: NextRequest,
  ctx: { params: Promise<{ path: string[] }> }
) {
  return proxyHandler(request, ctx);
}

export async function DELETE(
  request: NextRequest,
  ctx: { params: Promise<{ path: string[] }> }
) {
  return proxyHandler(request, ctx);
}
