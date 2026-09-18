import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { MoodleConnectionStatus } from "@/lib/types";

export interface MoodleStatusState {
  status: MoodleConnectionStatus | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

/**
 * Loads the persistent Moodle connection status and exposes a refresh
 * function so components can re-check after publishing.
 */
export function useMoodleStatus(): MoodleStatusState {
  const [status, setStatus] = useState<MoodleConnectionStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    setLoading(true);
    try {
      setStatus(await api.moodleStatus());
    } catch {
      setStatus(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  return { status, loading, refresh };
}