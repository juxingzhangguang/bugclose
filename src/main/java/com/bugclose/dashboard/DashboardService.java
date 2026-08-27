package com.bugclose.dashboard;

import com.bugclose.auth.AccessDeniedException;
import com.bugclose.auth.AccessScope;
import com.bugclose.bug.BugService;
import com.bugclose.doc.Document;
import com.bugclose.doc.DocumentRepository;
import com.bugclose.requirement.Requirement;
import com.bugclose.requirement.RequirementRepository;
import com.bugclose.testcase.TestCase;
import com.bugclose.testcase.TestCaseRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 看板聚合统计：复用 Bug 统计，并补充测试用例（含通过率）、需求、文档维度。
 * 数据可见性与各模块一致：普通用户只统计其绑定项目内的数据。
 */
@Service
@Transactional(readOnly = true)
public class DashboardService {

    private final BugService bugService;
    private final TestCaseRepository testCaseRepository;
    private final RequirementRepository requirementRepository;
    private final DocumentRepository documentRepository;
    private final AccessScope accessScope;

    public DashboardService(BugService bugService,
                            TestCaseRepository testCaseRepository,
                            RequirementRepository requirementRepository,
                            DocumentRepository documentRepository,
                            AccessScope accessScope) {
        this.bugService = bugService;
        this.testCaseRepository = testCaseRepository;
        this.requirementRepository = requirementRepository;
        this.documentRepository = documentRepository;
        this.accessScope = accessScope;
    }

    public Map<String, Object> statistics() {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("bug", bugService.statistics());
        result.put("testCase", testCaseStatistics());
        result.put("requirement", requirementStatistics());
        result.put("doc", docStatistics());
        return result;
    }

    private Map<String, Object> testCaseStatistics() {
        List<TestCase> visible = testCaseRepository.findAll().stream()
                .filter(tc -> isVisible(tc.getProjectId()))
                .toList();

        Map<TestCase.ExecStatus, Long> byStatus = new EnumMap<>(TestCase.ExecStatus.class);
        for (TestCase.ExecStatus s : TestCase.ExecStatus.values()) {
            byStatus.put(s, 0L);
        }
        for (TestCase tc : visible) {
            if (tc.getStatus() != null) {
                byStatus.merge(tc.getStatus(), 1L, Long::sum);
            }
        }

        long pass = byStatus.getOrDefault(TestCase.ExecStatus.PASS, 0L);
        long executed = visible.size() - byStatus.getOrDefault(TestCase.ExecStatus.NOT_RUN, 0L);
        double passRate = executed == 0 ? 0 : Math.round(pass * 1000.0 / executed) / 10.0;

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("total", visible.size());
        result.put("byStatus", byStatus);
        result.put("executed", executed);
        result.put("passRate", passRate);
        return result;
    }

    private Map<String, Object> requirementStatistics() {
        List<Requirement> visible = requirementRepository.findAll().stream()
                .filter(r -> isVisible(r.getProjectId()))
                .toList();

        Map<Requirement.ReqStatus, Long> byStatus = new EnumMap<>(Requirement.ReqStatus.class);
        for (Requirement.ReqStatus s : Requirement.ReqStatus.values()) {
            byStatus.put(s, 0L);
        }
        for (Requirement r : visible) {
            if (r.getStatus() != null) {
                byStatus.merge(r.getStatus(), 1L, Long::sum);
            }
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("total", visible.size());
        result.put("byStatus", byStatus);
        return result;
    }

    private Map<String, Object> docStatistics() {
        List<Document> visible = documentRepository.findAll().stream()
                .filter(d -> isVisible(d.getProjectId()))
                .toList();

        Map<Document.DocCategory, Long> byCategory = new EnumMap<>(Document.DocCategory.class);
        for (Document.DocCategory c : Document.DocCategory.values()) {
            byCategory.put(c, 0L);
        }
        for (Document d : visible) {
            if (d.getCategory() != null) {
                byCategory.merge(d.getCategory(), 1L, Long::sum);
            }
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("total", visible.size());
        result.put("byCategory", byCategory);
        return result;
    }

    /** 与 BugService.statistics 一致的可见性过滤：不可见的项目直接跳过 */
    private boolean isVisible(Long projectId) {
        try {
            accessScope.requireVisible(projectId);
            return true;
        } catch (AccessDeniedException e) {
            return false;
        }
    }
}
