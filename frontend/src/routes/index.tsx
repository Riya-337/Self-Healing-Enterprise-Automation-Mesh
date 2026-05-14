import { createFileRoute } from "@tanstack/react-router";
import { Dashboard } from "@/components/dashboard/Dashboard";

export const Route = createFileRoute("/")({
  component: Index,
  ssr: false,
  head: () => ({
    meta: [
      { title: "SentiHealth — Security Operations Dashboard" },
      { name: "description", content: "Live SentiHealth security operations dashboard with real-time threat detections, ML ensemble metrics, and blockchain audit ledger." },
    ],
  }),
});

function Index() {
  return <Dashboard />;
}
