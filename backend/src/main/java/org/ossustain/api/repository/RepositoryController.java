package org.ossustain.api.repository;

import org.ossustain.api.dto.MetricPointResponse;
import org.ossustain.api.dto.PageResponse;
import org.ossustain.api.dto.PredictionDetailResponse;
import org.ossustain.api.dto.PredictionResponse;
import org.ossustain.api.dto.RepositoryDetailResponse;
import org.ossustain.api.dto.RepositorySummaryResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/v1/repositories")
public class RepositoryController {
    private final RepositoryReadService repositoryReadService;
    private final RepositoryAnalyticsReadService analyticsReadService;

    public RepositoryController(
            RepositoryReadService repositoryReadService,
            RepositoryAnalyticsReadService analyticsReadService) {
        this.repositoryReadService = repositoryReadService;
        this.analyticsReadService = analyticsReadService;
    }

    @GetMapping
    public PageResponse<RepositorySummaryResponse> list(
            @RequestParam(required = false) String risk,
            @RequestParam(required = false) String sizeGroup,
            @RequestParam(name = "q", required = false) String query,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "25") int pageSize,
            @RequestParam(defaultValue = "fullName") String sort,
            @RequestParam(defaultValue = "asc") String direction) {
        return repositoryReadService.list(risk, sizeGroup, query, page, pageSize, sort, direction);
    }

    @GetMapping("/{id}")
    public RepositoryDetailResponse get(@PathVariable long id) {
        return repositoryReadService.get(id);
    }

    @GetMapping("/{id}/metrics")
    public List<MetricPointResponse> metrics(@PathVariable long id) {
        return analyticsReadService.metrics(id);
    }

    @GetMapping("/{id}/predictions")
    public List<PredictionResponse> predictions(@PathVariable long id) {
        return analyticsReadService.history(id);
    }

    @GetMapping("/{id}/predictions/latest")
    public PredictionDetailResponse latestPrediction(@PathVariable long id) {
        return analyticsReadService.latest(id);
    }
}
