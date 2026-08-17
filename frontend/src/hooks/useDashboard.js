import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchDashboard } from '../api/dashboardApi'
import { runtimeConfig } from '../config/runtime'

export function useDashboard(range) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const abortRef = useRef(null)

  const load = useCallback(
    async ({ background = false } = {}) => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller
      let timedOut = false
      const timeout = window.setTimeout(() => {
        timedOut = true
        controller.abort()
      }, runtimeConfig.dashboardRequestTimeoutMs)

      if (background) setIsRefreshing(true)
      else setIsLoading(true)
      setError(null)

      try {
        const snapshot = await fetchDashboard(range, {
          signal: controller.signal,
        })
        setData(snapshot)
      } catch (requestError) {
        if (
          abortRef.current === controller &&
          (timedOut || requestError.name !== 'AbortError')
        ) {
          setError(requestError)
        }
      } finally {
        window.clearTimeout(timeout)
        if (abortRef.current === controller) {
          setIsLoading(false)
          setIsRefreshing(false)
        }
      }
    },
    [range],
  )

  useEffect(() => {
    const initialLoad = window.setTimeout(() => load(), 0)
    const interval = window.setInterval(
      () => load({ background: true }),
      runtimeConfig.dashboardRefreshIntervalMs,
    )

    return () => {
      window.clearTimeout(initialLoad)
      window.clearInterval(interval)
      abortRef.current?.abort()
    }
  }, [load])

  return {
    data: data?.range === range ? data : null,
    error,
    isLoading,
    isRefreshing,
    refresh: () => load({ background: true }),
  }
}
