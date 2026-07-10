from rest_framework.pagination import PageNumberPagination


class LargePageNumberPagination(PageNumberPagination):
    """Default pagination for the whole API.

    Identical to DRF's PageNumberPagination except it actually honors a
    `page_size` query param (capped at 1000) instead of silently ignoring
    it. The frontend depends on requesting larger pages in a few places —
    offline sync, report/bulk-import pickers, and "load everything for
    client-side filtering" views — so without `page_size_query_param` set,
    every list endpoint was hard-capped at 20 rows regardless of what the
    client asked for.
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 1000
