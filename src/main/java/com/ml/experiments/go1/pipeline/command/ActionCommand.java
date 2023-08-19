package com.ml.experiments.go1.pipeline.command;

import java.util.Map;

public interface ActionCommand {
    void execute();

    void configure(Map<String, Object> params);
}
