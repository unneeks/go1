package com.ml.experiments.go1.pipeline.model;

import com.ml.experiments.go1.pipeline.command.ActionCommand;

public class SubProcess {
    String name;
    String processtype;
     Action action;
    public String getName() {
        return name;
    }
    public void setName(String name) {
        this.name = name;
    }
    public String getProcesstype() {
        return processtype;
    }
    public void setProcesstype(String processtype) {
        this.processtype = processtype;
    }
    public Action getAction() {
        return action;
    }
    public void setAction(Action action) {
        this.action = action;
    }
    public void setActionCommand(ActionCommand actionCommand) {
    }
}