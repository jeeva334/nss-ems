import { useCallback, useEffect, useState } from "react";

export function useAsync(fn) {
  const [state, setState] = useState({ loading: true, data: null, error: null });
  const run = useCallback(() => {
    setState({ loading: true, data: null, error: null });
    Promise.resolve().then(() => fn()).then(
      (data) => setState({ loading: false, data, error: null }),
      (error) => setState({ loading: false, data: null, error })
    );
  }, [fn]);
  useEffect(run, [run]);
  return { ...state, retry: run };
}
