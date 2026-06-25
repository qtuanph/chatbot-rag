import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";

export default auth((req) => {
  const { pathname } = req.nextUrl;
  const isLoggedIn = !!req.auth;
  const role = req.auth?.role;

  let response: NextResponse | undefined;

  // Public routes
  if (pathname === "/login") {
    if (isLoggedIn) {
      response = NextResponse.redirect(
        new URL(role === "platform_admin" ? "/admin" : "/chat", req.nextUrl),
      );
    }
  }

  // Root route
  else if (pathname === "/") {
    if (isLoggedIn) {
      response = NextResponse.redirect(
        new URL(role === "platform_admin" ? "/admin" : "/chat", req.nextUrl),
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
  else if (pathname.startsWith("/admin") && role !== "platform_admin") {
    response = NextResponse.redirect(new URL("/chat", req.nextUrl));
  }

  if (!response) {
    response = NextResponse.next();
  }

  // Add security headers
  const isDevelopment = process.env.NODE_ENV !== "production";
  const connectSrc = isDevelopment ? "'self' ws: http://localhost:* ws://localhost:*" : "'self'";

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
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
