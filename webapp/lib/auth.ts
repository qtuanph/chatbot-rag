import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { authApi } from "@/lib/api-client";

export const { handlers, auth, signIn, signOut } = NextAuth({
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
          // Login to backend → get JWT
          const tokenRes = await authApi.login({
            username: credentials.username as string,
            password: credentials.password as string,
          });

          // Get user info with token
          const user = await authApi.getMe(tokenRes.access_token);

          return {
            id: user.user_id,
            name: user.username,
            role: user.role,
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
      // Initial sign in: persist token + role
      if (user) {
        token.accessToken = (user as { token: string }).token;
        token.role = (user as { role: string }).role;
        token.userId = user.id;
      }
      return token;
    },
    async session({ session, token }) {
      // Expose to client
      session.accessToken = token.accessToken as string;
      session.role = token.role as string;
      session.userId = token.userId as string;
      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
  session: {
    strategy: "jwt",
    maxAge: 60 * 60, // 1 hour (match backend JWT expiry)
  },
  secret: process.env.NEXTAUTH_SECRET,
});

// Type augmentation for next-auth
declare module "next-auth" {
  interface Session {
    accessToken: string;
    role: string;
    userId: string;
  }
  interface User {
    role?: string;
    token?: string;
  }
}

export const authOptions = { providers: [Credentials] };
