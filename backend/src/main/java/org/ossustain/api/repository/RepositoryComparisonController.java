package org.ossustain.api.repository;

import org.ossustain.api.dto.RepositoryComparisonResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/v1/compare")
public class RepositoryComparisonController {
    private final RepositoryComparisonReadService comparisonReadService;

    public RepositoryComparisonController(RepositoryComparisonReadService comparisonReadService) {
        this.comparisonReadService = comparisonReadService;
    }

    @GetMapping
    public RepositoryComparisonResponse compare(@RequestParam List<Long> ids) {
        return comparisonReadService.compare(ids);
    }
}
