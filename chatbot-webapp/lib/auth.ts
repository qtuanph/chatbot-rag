import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";

import { authApi } from "@/lib/api-client";

type AuthUser = {
  id?: string;
  role?: string;
  tenantId?: string | null;
  token?: string;
};

export const { handlers, auth, signIn, signOut } = NextAuth({
  trustHost: true,
  providers: [
    Credentials({
      name: "credentials",
      credentials: {
        username: { label: "Username", type: "text" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.username || !credentials?.password) {
          return null;
        }

        try {
          const tokenRes = await authApi.login({
            username: credentials.username as string,
            password: credentials.password as string,
          });

          const user = await authApi.getMe(tokenRes.access_token);

          return {
            id: user.user_id,
            name: user.username,
            role: user.role,
            tenantId: user.tenant_id,
            token: tokenRes.access_token,
          };
        } catch {
          return null;
        }
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        const authUser = user as AuthUser;
        token.accessToken = authUser.token;
        token.role = authUser.role;
        token.userId = user.id;
        token.tenantId = authUser.tenantId ?? null;
        token.accessTokenExpires = Math.floor(Date.now() / 1000) + 3600;
      }

      const now = Math.floor(Date.now() / 1000);
      if (token.accessTokenExpires && now > token.accessTokenExpires - 300) {
        token.expired = "true";
      }

      return token;
    },
    async session({ session, token }) {
      session.role = token.role as string;
      session.userId = token.userId as string;
      session.tenantId = (token.tenantId as string | null | undefined) ?? null;
      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
  session: {
    strategy: "jwt",
    maxAge: 60 * 60,
  },
  secret: process.env.NEXTAUTH_SECRET,
});

declare module "next-auth" {
  interface Session {
    role: string;
    userId: string;
    tenantId: string | null;
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

export const authOptions = { providers: [Credentials] };
