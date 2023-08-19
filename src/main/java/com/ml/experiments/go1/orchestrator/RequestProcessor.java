package com.ml.experiments.go1.orchestrator;

import com.ml.experiments.go1.orchestrator.model.Request;
import com.ml.experiments.go1.pipeline.builder.PipelineBuilder;
import com.ml.experiments.go1.pipeline.executer.PipelineExecutor;
import com.ml.experiments.go1.pipeline.model.Pipeline;

class RequestProcessor {
    public void process(Request request) throws Exception {
        PipelineRepository repo = new PipelineRepository();
        String pipeline = repo.getPipeline(request);
        PipelineBuilder builder = new PipelineBuilder(pipeline);
        Pipeline builtPipeline = builder.build();
        PipelineExecutor executor = new PipelineExecutor();
        executor.execute(builtPipeline);
    }
}