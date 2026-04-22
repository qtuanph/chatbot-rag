import { getToken } from "next-auth/jwt";
import type { NextRequest } from "next/server";

const API_INTERNAL = process.env.API_INTERNAL_URL!;

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

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
    init.body = request.body;
    // duplex required for streaming request bodies in Node.js fetch
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (init as any).duplex = "half";
  }

  const backendRes = await fetch(backendUrl, init);

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
