"""AttackSurfaceIndex.endpoints is ONE instance shared by every DeepAgent in
a scan; ingest_response() is called on every HTTP probe ANY agent makes,
concurrently (asyncio.gather). A real /deep scan crashed with a traceback
proving exactly this: DeepCMDiAgent, DeepSSTIAgent and DeepPathTraversalAgent
all hit "dictionary changed size during iteration" at
`for path, profile in self.asi.endpoints.items()` while another agent's
ingest_response() inserted a new endpoint mid-loop. snapshot_endpoints()
fixes it; these tests reproduce the race under real threads (the asyncio
single-thread model alone wouldn't prove this reliably) and pin that the
fix holds.
"""
import threading

from backend.deepagents.attack_surface_index import AttackSurfaceIndex


def test_snapshot_endpoints_is_a_real_copy_not_a_view():
    asi = AttackSurfaceIndex()
    asi.ingest_response("/api/a", "GET", "", 200, "", {})
    snap = asi.snapshot_endpoints()
    asi.ingest_response("/api/b", "GET", "", 200, "", {})
    assert "/api/b" not in snap  # snapshot frozen at the time it was taken
    assert "/api/b" in asi.endpoints


def test_concurrent_ingest_and_snapshot_iteration_never_raises():
    """Reproduces the real crash: one thread inserts new endpoints via
    ingest_response() while another iterates — via the OLD direct
    `.endpoints.items()` this reliably raises RuntimeError under real
    thread concurrency; via snapshot_endpoints() it must never raise."""
    asi = AttackSurfaceIndex()
    errors = []
    stop = threading.Event()

    def writer():
        i = 0
        while not stop.is_set():
            asi.ingest_response(f"/api/endpoint-{i}", "GET", "", 200, "", {})
            i += 1

    def reader():
        try:
            for _ in range(500):
                total = 0
                for path, profile in asi.snapshot_endpoints().items():
                    total += len(path)
        except Exception as e:  # pragma: no cover - the race this test guards
            errors.append(e)

    writer_thread = threading.Thread(target=writer)
    reader_threads = [threading.Thread(target=reader) for _ in range(4)]
    writer_thread.start()
    for t in reader_threads:
        t.start()
    for t in reader_threads:
        t.join()
    stop.set()
    writer_thread.join()

    assert not errors, f"snapshot-based iteration raised: {errors}"


def test_direct_dict_iteration_is_the_actual_race_this_fix_avoids():
    """Documents WHY the fix is needed: iterating self.endpoints directly
    (the old, buggy pattern) really does raise under this same concurrency,
    so this isn't a defensive-only change."""
    asi = AttackSurfaceIndex()
    errors = []
    stop = threading.Event()

    def writer():
        i = 0
        while not stop.is_set():
            asi.ingest_response(f"/api/endpoint-{i}", "GET", "", 200, "", {})
            i += 1

    def reader():
        try:
            for _ in range(2000):
                for path, profile in asi.endpoints.items():  # the OLD buggy pattern
                    pass
        except RuntimeError as e:
            errors.append(e)

    writer_thread = threading.Thread(target=writer)
    reader_threads = [threading.Thread(target=reader) for _ in range(4)]
    writer_thread.start()
    for t in reader_threads:
        t.start()
    for t in reader_threads:
        t.join()
    stop.set()
    writer_thread.join()

    assert errors, "expected the unprotected direct-iteration pattern to race and raise"
