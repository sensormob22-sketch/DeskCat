import statistics
import time
from .rendering.panda import PandaRenderer
from .states import State, StateMachine


def benchmark(model, frames, width, height):
    renderer = PandaRenderer(model, width, height)
    try:
        machine = StateMachine()
        machine.transition(State.WALK)
        machine.update(.3)
        for _ in range(10):
            renderer.frame(1/60, machine.weights, width, height)
        durations = []
        for _ in range(frames):
            start = time.perf_counter()
            renderer.frame(1/60, machine.weights, width, height)
            durations.append(time.perf_counter()-start)
        return {'driver': renderer.driver, 'frames': frames, 'width': width, 'height': height,
                'median_ms': round(statistics.median(durations)*1000, 3),
                'p95_ms': round(sorted(durations)[int((frames-1)*.95)]*1000, 3),
                'mean_fps': round(1/statistics.mean(durations), 2),
                'scope': 'animation + offscreen render + RGBA readback + QImage; excludes Qt paint/DWM'}
    finally:
        renderer.close()
