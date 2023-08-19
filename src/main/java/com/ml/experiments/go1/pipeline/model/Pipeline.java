package com.ml.experiments.go1.pipeline.model;
import java.util.List;

// Base models for parsing JSON
public class Pipeline {
    String Soid;
    String requestType;
    String requestSubType;
    List<String> scopes;
    public List<Process> processes;
    public List<Process> getProcesses() {
        return processes;
    }
    public void setProcesses(List<Process> processes) {
        this.processes = processes;
    }
}
