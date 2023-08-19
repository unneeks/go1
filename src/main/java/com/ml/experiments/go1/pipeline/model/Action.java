package com.ml.experiments.go1.pipeline.model;

import java.util.Map;

public class Action {
    String method;
    Map<String, Object> params;
    String postprocess;
    public String getMethod() {
        return method;
    }
    public void setMethod(String method) {
        this.method = method;
    }
    public Map<String, Object> getParams() {
        return params;
    }
    public void setParams(Map<String, Object> params) {
        this.params = params;
    }
    public String getPostprocess() {
        return postprocess;
    }
    public void setPostprocess(String postprocess) {
        this.postprocess = postprocess;
    }
}