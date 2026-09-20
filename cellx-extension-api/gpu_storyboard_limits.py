"""Shared limits for the home-GPU presenter + photos mode only."""
MIN_SECONDS=15
MAX_SECONDS=300
MAX_OPENING_SECONDS=20
MAX_OPENING_CHARS=100
MAX_SCENE_CHARS=6000
MAX_NARRATION_CHARS=10000
MAX_RESULT_BYTES=160*1024*1024


def tolerance(target):
    return min(3.,target*.02,MAX_SECONDS-target+.1)


def valid_duration(value):
    return type(value) is int and MIN_SECONDS<=value<=MAX_SECONDS
