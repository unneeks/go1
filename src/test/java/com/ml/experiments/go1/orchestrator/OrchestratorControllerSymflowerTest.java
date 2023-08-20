package com.ml.experiments.go1.orchestrator;

import static org.mockito.Mockito.when;

import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(OrchestratorController.class)
public class OrchestratorControllerSymflowerTest {
	
    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private OrchestratorService orchestratorService;

    @Test
	public void execute1() {
		// Book mockBook = new Book(1L, "Sample Book", "Sample Author");
        
        when(orchestratorService.executePipeline(null)).thenReturn("Hello World") ;
        
        mockMvc.perform(get("/books/1"))
               .andExpect(status().isOk())
               .andExpect(jsonPath("$.id").value(1L))
               .andExpect(jsonPath("$.title").value("Sample Book"))
               .andExpect(jsonPath("$.author").value("Sample Author"));
    }
}

