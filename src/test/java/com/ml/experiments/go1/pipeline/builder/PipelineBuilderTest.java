package com.ml.experiments.go1.pipeline.builder;

import com.ml.experiments.go1.pipeline.model.Pipeline;
import org.junit.jupiter.api.*;
import static org.junit.jupiter.api.Assertions.*;

public class PipelineBuilderTest {
	@Test
	public void build() throws Exception {
		PipelineBuilder p = new PipelineBuilder("abc");
		Pipeline expected = new Pipeline();
		Pipeline actual = p.build();

		assertEquals(expected, actual);
	}
}
