from openflow.migrate.transformers import ConvertLogCalls, transform


def test_log_Info_to_logger_info():
    before = 'self.log.Info("hello")\n'
    after = transform(before, ConvertLogCalls())
    assert "logger.info" in after


def test_log_Warning_to_logger_warning():
    before = 'self.log.Warning("warn")\n'
    after = transform(before, ConvertLogCalls())
    assert "logger.warning" in after


def test_log_Error_to_logger_error():
    before = 'self.log.Error("oh no")\n'
    after = transform(before, ConvertLogCalls())
    assert "logger.error" in after


def test_log_Debug_to_logger_debug():
    before = 'self.log.Debug("d")\n'
    after = transform(before, ConvertLogCalls())
    assert "logger.debug" in after


def test_post_self_strip_form_also_handled():
    before = 'log.Info("after self-strip")\n'
    after = transform(before, ConvertLogCalls())
    assert "logger.info" in after
