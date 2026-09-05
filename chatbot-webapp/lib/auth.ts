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
        } catch (error) {
          console.error("[NextAuth Authorize Error]:", error);
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
        // 7 days token expiration
        token.accessTokenExpires = Math.floor(Date.now() / 1000) + 7 * 24 * 3600;
      }

      const now = Math.floor(Date.now() / 1000);
      if (token.accessTokenExpires && now > token.accessTokenExpires - 300) {
        token.expired = "true";
      }

      return token;
    },
    async session({ session, token }) {
      if (token.expired === "true") {
        return null as unknown as typeof session;
      }
      session.role = token.role as string;
      session.userId = token.userId as string;
      session.tenantId = (token.tenantId as string | null | undefined) ?? null;
      session.accessToken = token.accessToken as string;
      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
  session: {
    strategy: "jwt",
    maxAge: 7 * 24 * 60 * 60, // 7 days
  },
  secret: process.env.NEXTAUTH_SECRET,
});

export const authOptions = { providers: [Credentials] };
