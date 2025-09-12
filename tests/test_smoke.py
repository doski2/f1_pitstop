def test_import_f1m_modules():
    # Smoke test: ensure core modules import and expose expected callables
    import f1m.planner as planner
    import f1m.telemetry as telemetry

    assert hasattr(telemetry, "load_session_csv"), "telemetry.load_session_csv missing"
    assert hasattr(planner, "enumerate_plans"), "planner.enumerate_plans missing"
