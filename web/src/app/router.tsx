import { createBrowserRouter } from "react-router-dom";

import { AppShell } from "../components/AppShell";
import { DashboardPage } from "../pages/DashboardPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { RunDetailPage } from "../pages/RunDetailPage";
import { RunsPage } from "../pages/RunsPage";
import { StartRunPage } from "../pages/StartRunPage";

export const router = createBrowserRouter([{ path: "/", element: <AppShell />, children: [
  { index: true, element: <DashboardPage /> },
  { path: "runs/new", element: <StartRunPage /> },
  { path: "runs", element: <RunsPage /> },
  { path: "runs/:runId", element: <RunDetailPage /> },
  { path: "*", element: <NotFoundPage /> }
] }]);
