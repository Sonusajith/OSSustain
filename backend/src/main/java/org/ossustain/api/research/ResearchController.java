package org.ossustain.api.research;

import org.ossustain.api.dto.DatasetSummaryResponse;
import org.ossustain.api.dto.EvaluationResponse;
import org.ossustain.api.dto.FeatureImportanceResponse;
import org.ossustain.api.dto.LabelDefinitionResponse;
import org.ossustain.api.dto.ModelVersionResponse;
import org.ossustain.api.dto.PageResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/research")
public class ResearchController {
    private final ResearchReadService researchReadService;

    public ResearchController(ResearchReadService researchReadService) {
        this.researchReadService = researchReadService;
    }

    @GetMapping("/models")
    public PageResponse<ModelVersionResponse> models(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "50") int pageSize) {
        return researchReadService.models(page, pageSize);
    }

    @GetMapping("/evaluations")
    public PageResponse<EvaluationResponse> evaluations(
            @RequestParam(required = false) String split,
            @RequestParam(required = false) String featureSet,
            @RequestParam(required = false) String stratum,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "50") int pageSize) {
        return researchReadService.evaluations(split, featureSet, stratum, page, pageSize);
    }

    @GetMapping("/feature-importance")
    public PageResponse<FeatureImportanceResponse> featureImportance(
            @RequestParam(required = false) Long modelVersionId,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "50") int pageSize) {
        return researchReadService.featureImportance(modelVersionId, page, pageSize);
    }

    @GetMapping("/dataset-summary")
    public DatasetSummaryResponse datasetSummary() {
        return researchReadService.datasetSummary();
    }

    @GetMapping("/label-definition")
    public LabelDefinitionResponse labelDefinition() {
        return researchReadService.labelDefinition();
    }
}
