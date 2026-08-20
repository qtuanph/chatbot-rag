import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";

export default auth((req) => {
  const { pathname } = req.nextUrl;
  const isLoggedIn = !!req.auth;
  const role = req.auth?.role;

  let response: NextResponse | undefined;

  // Public routes
  if (pathname === "/login") {
    const hasErrorParam = req.nextUrl.searchParams.has("error");
    if (isLoggedIn && !hasErrorParam) {
      response = NextResponse.redirect(
        new URL(role === "platform_admin" ? "/admin" : "/analytics", req.nextUrl),
      );
    }
  }

  // Root route
  else if (pathname === "/") {
    if (isLoggedIn) {
      response = NextResponse.redirect(
        new URL(role === "platform_admin" ? "/admin" : "/analytics", req.nextUrl),
      );
    } else {
      response = NextResponse.redirect(new URL("/login", req.nextUrl));
    }
  }

  // Protected routes: redirect to login if not authenticated
  else if (!isLoggedIn && !pathname.startsWith("/api/auth") && !pathname.startsWith("/api/bep")) {
    const loginUrl = new URL("/login", req.nextUrl);
    loginUrl.searchParams.set("callbackUrl", pathname);
    response = NextResponse.redirect(loginUrl);
  }

  // Admin routes: require platform admin role
  else if (
    pathname.startsWith("/admin") &&
    role !== "platform_admin" &&
    !(role === "tenant_admin" && pathname.startsWith("/admin/conversations"))
  ) {
    response = NextResponse.redirect(new URL("/analytics", req.nextUrl));
  }

  // Guides for platform admin only: block tenant_admin
  else if ((pathname.startsWith("/guides/providers") || pathname.startsWith("/guides/tenants")) && role !== "platform_admin") {
    response = NextResponse.redirect(new URL("/analytics", req.nextUrl));
  }

  // Tenant-only routes: redirect platform_admin to the corresponding /admin pages
  else if (role === "platform_admin") {
    if (pathname === "/documents") {
      response = NextResponse.redirect(new URL("/admin/documents", req.nextUrl));
    } else if (pathname === "/faqs") {
      response = NextResponse.redirect(new URL("/admin/faqs", req.nextUrl));
    } else if (pathname === "/analytics") {
      response = NextResponse.redirect(new URL("/admin/analytics", req.nextUrl));
    }
  }

  if (!response) {
    response = NextResponse.next();
  }

  // Add security headers
  const connectSrc = "'self' ws: https: http://localhost:* ws://localhost:* https://*.sse.net.vn";


  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  response.headers.set("Permissions-Policy", "geolocation=(), microphone=(), camera=(), payment=()");
  response.headers.set("X-DNS-Prefetch-Control", "on");
  response.headers.set("Content-Security-Policy", `default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src ${connectSrc};`);
  response.headers.set("Strict-Transport-Security", "max-age=31536000; includeSubDomains");

  return response;
});

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|Js/|Css/|downloads/|api/health).*)'
  ]
};
