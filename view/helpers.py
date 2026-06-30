# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Olivier Meyer

# Standard library
import time


def get_remaining_seconds(end):
    if end is None:
        return 0
    return max(0, end - int(time.time()))


def shorten_str(text, length):
    if not text:
        return ''
    return text if len(text) < length else text[:length] + '...'
