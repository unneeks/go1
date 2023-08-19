package com.ml.experiments.go1.pipeline.executer;
import com.ml.experiments.go1.pipeline.command.ActionCommand;
import com.ml.experiments.go1.pipeline.command.ActionCommandFactory;
import com.ml.experiments.go1.pipeline.model.Pipeline;
import com.ml.experiments.go1.pipeline.model.Process;
import com.ml.experiments.go1.pipeline.model.SubProcess;

public class PipelineExecutor {
    public void execute(Pipeline pipeline) {
        for (Process process : pipeline.getProcesses()) {
            for (SubProcess subProcess : process.subprocess) {
                ActionCommand actionCommand = ActionCommandFactory.getActionCommand(subProcess.getAction().getMethod());
                actionCommand.execute();
            }
        }
    }
}
