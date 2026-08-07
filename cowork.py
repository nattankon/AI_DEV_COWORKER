try:
    from .cli import run
except ImportError:
    from cli import run


if __name__ == "__main__":
    run()
