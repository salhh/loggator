import { auth } from "@/auth";

export default auth((req) => {
  const path = req.nextUrl.pathname;
  if (path.startsWith("/login") || path.startsWith("/logout") || path.startsWith("/api/auth"))
    return;
  if (req.auth) return;
  const login = new URL("/login", req.url);
  login.searchParams.set("callbackUrl", `${path}${req.nextUrl.search}`);
  return Response.redirect(login);
});

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)",
  ],
};
