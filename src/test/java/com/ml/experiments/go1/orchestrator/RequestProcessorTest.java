package com.ml.experiments.go1.orchestrator;

import com.ml.experiments.go1.orchestrator.model.Request;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import static org.mockito.Mockito.*;

import org.mockito.InjectMocks;
import org.mockito.Mock;

public class RequestProcessorTest {

    @Mock
    private PipelineRepository pipelineRepository;

    @InjectMocks
    private RequestProcessor requestProcessor;

    @BeforeEach
    public void setup() {
        // Initialize mocks
       
    }

    @Test
    public void testProcess() throws Exception {
        // Given
        Request mockRequest = new Request();
        mockRequest.setDoctype("payslip");
        mockRequest.setBusinessunit("lending");

        String mockPipeline = "new Pipeline();";  // Create a mock pipeline object
        // (Optional) You can populate mockPipeline with some predefined data

        // Mock the behavior of pipelineRepository to return the mockPipeline when called
        when(pipelineRepository.getPipeline(mockRequest)).thenReturn(mockPipeline);

        // Act
        requestProcessor.process(mockRequest);

        // Assert
        verify(pipelineRepository).getPipeline(mockRequest);  // Verify that the method was indeed called with the mockRequest
        // Add any other assertions as needed
    }
}

