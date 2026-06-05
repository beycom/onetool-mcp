import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AdminApi } from "./adminApi";
import { AdminFrame } from "./AdminFrame";

export function AdminApp() {
  const api = useMemo(() => new AdminApi(window.location), []);
  const queryClient = useQueryClient();
  const [selectedIdentity, setSelectedIdentity] = useState<string | null>(null);
  const instancesQuery = useQuery({
    queryKey: ["admin", api.adminOrigin, "instances"],
    queryFn: () => api.scan(),
    refetchInterval: 5_000,
    refetchOnWindowFocus: false,
  });
  const instances = instancesQuery.data ?? [];
  const selected = instances.find((instance) => instance.identity === selectedIdentity) ?? instances[0] ?? null;

  useEffect(() => {
    if (!selectedIdentity && selected) setSelectedIdentity(selected.identity);
  }, [selected, selectedIdentity]);

  const scan = useCallback(async () => {
    const next = await api.scan();
    queryClient.setQueryData(["admin", api.adminOrigin, "instances"], next);
    if (!selectedIdentity && next[0]) setSelectedIdentity(next[0].identity);
  }, [api, queryClient, selectedIdentity]);

  return (
    <AdminFrame
      instances={instances}
      selected={selected}
      error={instancesQuery.error instanceof Error ? instancesQuery.error.message : null}
      onScan={scan}
      onSelect={setSelectedIdentity}
    />
  );
}
