package com.ml.experiments.go1.pipeline.command;

public class ActionCommandFactory {
    public static ActionCommand getActionCommand(String method) {
        switch (method) {
            case "invokepaylsip":
                return new InvokePaylsipCommand();
            case "post":
                return new PostCommand();
            default:
                throw new IllegalArgumentException("Invalid action method: " + method);
        }
    }
}