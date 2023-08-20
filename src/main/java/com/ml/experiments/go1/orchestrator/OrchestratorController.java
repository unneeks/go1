package com.ml.experiments.go1.orchestrator;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.ml.experiments.go1.orchestrator.model.Request;

@RestController
@RequestMapping("/api/v1/orchestrator")
public class OrchestratorController {
    @Autowired
    OrchestratorService orchestratorService ;
    @RequestMapping("/execute")
    public String execute(Request request) {
        return "Hello World";
    }
}



