"""
Performance tracking for the TCF PPC Dashboard.
"""
import time
import streamlit as st
from contextlib import ContextDecorator

class PerfTimer(ContextDecorator):
    """
    Context manager and decorator for tracking execution time of blocks of code or functions.
    Logs timings into st.session_state._perf_timings.
    """
    def __init__(self, name: str):
        self.name = name
        self.start_time = None
        
        if '_perf_timings' not in st.session_state:
            st.session_state._perf_timings = {}

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = time.perf_counter()
        elapsed = end_time - self.start_time
        
        if self.name not in st.session_state._perf_timings:
            st.session_state._perf_timings[self.name] = []
            
        st.session_state._perf_timings[self.name].append(elapsed)
        return False
