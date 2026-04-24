import { getToken } from "next-auth/jwt";
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

  // Build fetch options
  const init: RequestInit = {
    method: request.method,
    headers,
  };

  // Forward body for non-GET/HEAD requests (handles JSON, FormData, SSE)
  if (request.method !== "GET" && request.method !== "HEAD") {
    // Clone body before forwarding (needed for retry)
    const bodyBlob = await request.blob();
    init.body = bodyBlob;
  }

  let backendRes: Response;
  try {
    backendRes = await fetch(backendUrl, init);
  } catch (err: unknown) {
    // Retry once on socket close (worker restart / transient error)
    const isSocketError =
      err instanceof TypeError ||
      (err instanceof Error && /socket|closed|econnrefused|econnreset/i.test(err.message));

    if (isSocketError) {
      try {
        backendRes = await fetch(backendUrl, init);
      } catch {
        return new Response(
          JSON.stringify({ detail: "Backend service unavailable. Please try again." }),
          { status: 502, headers: { "content-type": "application/json" } },
        );
      }
    } else {
      return new Response(
        JSON.stringify({ detail: "Backend request failed." }),
        { status: 502, headers: { "content-type": "application/json" } },
      );
    }
  }

  // Build response headers
  const responseHeaders = new Headers();
  const resContentType = backendRes.headers.get("content-type");
  if (resContentType) responseHeaders.set("content-type", resContentType);

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
