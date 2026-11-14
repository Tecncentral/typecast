"""Deep engine interface; runtime must announce fixed fallback until available."""
def run_deep(ctx, req):
    raise RuntimeError("Deep engine not configured")
