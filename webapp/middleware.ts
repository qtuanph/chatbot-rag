import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";

export default auth((req) => {
  const { pathname } = req.nextUrl;
  const isLoggedIn = !!req.auth;
  const role = req.auth?.role;

  // Public routes
  if (pathname.startsWith("/login")) {
    if (isLoggedIn) {
      return NextResponse.redirect(
        new URL(role === "admin" ? "/admin" : "/chat", req.nextUrl),
      );
    }
    return NextResponse.next();
  }

  // API routes (next-auth)
  if (pathname.startsWith("/api/auth")) {
    return NextResponse.next();
  }

  // Protected routes: redirect to login if not authenticated
  if (!isLoggedIn) {
    const loginUrl = new URL("/login", req.nextUrl);
    loginUrl.searchParams.set("callbackUrl", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Admin routes: require admin role
  if (pathname.startsWith("/admin") && role !== "admin") {
    return NextResponse.redirect(new URL("/chat", req.nextUrl));
  }

  return NextResponse.next();
});

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
