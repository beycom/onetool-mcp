import { createRootRoute, createRoute, createRouter, Outlet } from "@tanstack/react-router";
import { MockDisplayApp } from "../features/display/DisplayApp";
import { AdminApp } from "./AdminApp";

export function createAdminRouter() {
  const rootRoute = createRootRoute({ component: AdminRoot });
  const indexRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/",
    component: AdminApp,
  });
  const placeholderRoutes = ["config", "tools", "stats", "localhist", "servers", "security", "results"].map((path) =>
    createRoute({
      getParentRoute: () => rootRoute,
      path,
      component: AdminPlaceholder,
    }),
  );
  const routeTree = rootRoute.addChildren([indexRoute, ...placeholderRoutes]);
  return createRouter({ routeTree });
}

function AdminRoot() {
  return <Outlet />;
}

function AdminPlaceholder() {
  return <MockDisplayApp />;
}
