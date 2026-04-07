"use client";

import useSWR from "swr";

const fetcher = (url: string) =>
  fetch(url).then((r) => {
    if (!r.ok) throw new Error(`${r.status}`);
    return r.json();
  });

export function useFetch<T>(url: string | null, refreshInterval = 60000) {
  const { data, error, isLoading, mutate } = useSWR<T>(url, fetcher, {
    refreshInterval,
    revalidateOnFocus: false,
  });
  return { data, error, isLoading, mutate };
}
