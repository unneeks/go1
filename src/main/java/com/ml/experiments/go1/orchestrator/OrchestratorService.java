package com.ml.experiments.go1.orchestrator;

import org.springframework.stereotype.Service;

import com.ml.experiments.go1.orchestrator.model.Request;

@Service
public class OrchestratorService {
    
    public void  executePipeline(Request request) {
        PipelineRepository pipelineRepository = new PipelineRepository();
        String pipeline = pipelineRepository.getPipeline(request);
      
    }
}
