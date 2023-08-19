package com.ml.experiments.go1.pipeline.builder;
import com.ml.experiments.go1.pipeline.command.ActionCommand;
import com.ml.experiments.go1.pipeline.command.ActionCommandFactory;
import com.ml.experiments.go1.pipeline.model.Pipeline;
import com.ml.experiments.go1.pipeline.model.SubProcess;
import com.fasterxml.jackson.databind.ObjectMapper;  // Jackson library is used for JSON parsing

public class PipelineBuilder {
    private Pipeline pipeline;
    private String jsonDefinition;

    public PipelineBuilder(String jsonDefinition) {
        this.jsonDefinition = jsonDefinition;
    }


    public Pipeline build() throws Exception {
        // Deserialize the JSON into a Pipeline object
        ObjectMapper mapper = new ObjectMapper();
        pipeline = mapper.readValue(jsonDefinition, Pipeline.class);

        // For each process, iterate through subprocess and create ActionCommand for each action
        for (com.ml.experiments.go1.pipeline.model.Process process : pipeline.getProcesses()) {
            for (SubProcess subProcess : process.subprocess) {
                // Use the ActionCommandFactory to instantiate appropriate actions
                ActionCommand actionCommand = ActionCommandFactory.getActionCommand(subProcess.getAction().getMethod());
                
                // (Optional) If there's any other initial setup, postprocessing, or configuration
                // based on other fields, you can do them here. For example:
                 actionCommand.configure(subProcess.getAction().getParams());

                // (Note) You can also store the created actionCommand back to subProcess if needed
                 subProcess.setActionCommand(actionCommand);
            }
        }

        return pipeline;
    }
}


