package com.ml.experiments.go1.pipeline.model;

import java.util.List;

public class Process {
    int processId;
    String appname;
    Integer next;
    String route;
    String type;
    String onException;
    String namespace;
    public List<SubProcess> subprocess;
    public int getProcessId() {
        return processId;
    }
    public void setProcessId(int processId) {
        this.processId = processId;
    }
    public String getAppname() {
        return appname;
    }
    public void setAppname(String appname) {
        this.appname = appname;
    }
    public Integer getNext() {
        return next;
    }
    public void setNext(Integer next) {
        this.next = next;
    }
    public String getRoute() {
        return route;
    }
    public void setRoute(String route) {
        this.route = route;
    }
    public String getType() {
        return type;
    }
    public void setType(String type) {
        this.type = type;
    }
    public String getOnException() {
        return onException;
    }
    public void setOnException(String onException) {
        this.onException = onException;
    }
    public String getNamespace() {
        return namespace;
    }
    public void setNamespace(String namespace) {
        this.namespace = namespace;
    }
    public List<SubProcess> getSubprocess() {
        return subprocess;
    }
    public void setSubprocess(List<SubProcess> subprocess) {
        this.subprocess = subprocess;
    }
}