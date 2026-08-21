import "next-auth";
import "next-auth/jwt";

declare module "next-auth" {
  interface Session {
    role: string;
    userId: string;
    tenantId: string | null;
    accessToken?: string;
  }

  interface User {
    role?: string;
    token?: string;
    tenantId?: string | null;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    accessToken?: string;
    accessTokenExpires?: number;
    expired?: string;
    role?: string;
    userId?: string;
    tenantId?: string | null;
  }
}
