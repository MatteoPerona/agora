import { createBrowserRouter } from "react-router";
import { Home } from "./pages/Home";
import { SummonCouncil } from "./pages/SummonCouncil";
import { Debate } from "./pages/Debate";
import { Verdict } from "./pages/Verdict";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Home,
  },
  {
    path: "/summon",
    Component: SummonCouncil,
  },
  {
    path: "/debate/:debateId",
    Component: Debate,
  },
  {
    path: "/verdict/:debateId",
    Component: Verdict,
  },
]);
