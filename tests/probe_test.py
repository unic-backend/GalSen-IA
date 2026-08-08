def test_probe():
    import sys
    print("PATH[0:5] ->", sys.path[:5])
    import storage
    print("storage ->", storage.__file__, storage.__path__ if hasattr(storage, "__path__") else "")
    try:
        import memory_engine
        print("memory_engine ->", memory_engine.__file__)
    except Exception as e:
        print("memory_engine FAIL ->", e)
    assert True
