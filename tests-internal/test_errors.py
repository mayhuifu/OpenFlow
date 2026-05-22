from openflow import errors


def test_instrument_connect_error_subclasses_openflow_error():
    assert issubclass(errors.InstrumentConnectError, errors.OpenFlowError)


def test_migration_error_subclasses_openflow_error():
    assert issubclass(errors.MigrationError, errors.OpenFlowError)


def test_openflow_error_subclasses_exception():
    assert issubclass(errors.OpenFlowError, Exception)


def test_instrument_connect_error_carries_resource_in_message():
    err = errors.InstrumentConnectError(resource="TCPIP::1.2.3.4::INSTR",
                                        cause="timeout")
    assert "TCPIP::1.2.3.4::INSTR" in str(err)
    assert "timeout" in str(err)
