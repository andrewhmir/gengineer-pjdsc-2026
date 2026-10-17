"""The signal path: frames in, one outcome out.

Nothing under this package imports FastAPI or reads the wall clock, so every module here can be
exercised with a synthetic window and a fixed number of samples.
"""
