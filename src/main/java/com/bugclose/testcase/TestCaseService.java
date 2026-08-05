package com.bugclose.testcase;

import com.bugclose.auth.AccessScope;
import jakarta.persistence.criteria.Predicate;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * 测试用例业务逻辑
 */
@Service
@Transactional
public class TestCaseService {

    private final TestCaseRepository testCaseRepository;
    private final AccessScope accessScope;

    public TestCaseService(TestCaseRepository testCaseRepository, AccessScope accessScope) {
        this.testCaseRepository = testCaseRepository;
        this.accessScope = accessScope;
    }

    /** 条件查询：项目 / 执行状态 / 优先级 / 关键字（标题、模块） */
    @Transactional(readOnly = true)
    public List<TestCase> search(Long projectId, TestCase.ExecStatus status,
                                 TestCase.CasePriority priority, String keyword) {
        Specification<TestCase> spec = (root, query, cb) -> {
            List<Predicate> predicates = new ArrayList<>();
            if (!accessScope.isAllAccess()) {
                predicates.add(root.get("projectId").in(accessScope.visibleProjectIds()));
            }
            if (projectId != null) predicates.add(cb.equal(root.get("projectId"), projectId));
            if (status != null) predicates.add(cb.equal(root.get("status"), status));
            if (priority != null) predicates.add(cb.equal(root.get("priority"), priority));
            if (keyword != null && !keyword.isBlank()) {
                String like = "%" + keyword.trim().toLowerCase() + "%";
                predicates.add(cb.or(
                        cb.like(cb.lower(root.get("title")), like),
                        cb.like(cb.lower(root.get("module")), like)));
            }
            return cb.and(predicates.toArray(new Predicate[0]));
        };
        return testCaseRepository.findAll(spec, Sort.by("id"));
    }

    @Transactional(readOnly = true)
    public TestCase findById(Long id) {
        TestCase testCase = testCaseRepository.findById(id)
                .orElseThrow(() -> new TestCaseNotFoundException(id));
        accessScope.requireVisible(testCase.getProjectId());
        return testCase;
    }

    public TestCase create(TestCase testCase) {
        validateRequired(testCase);
        accessScope.requireProjectOnWrite(testCase.getProjectId());
        testCase.setId(null);
        testCase.setSeq(testCaseRepository.findMaxSeqInProject(testCase.getProjectId()) + 1);
        if (testCase.getPriority() == null) testCase.setPriority(TestCase.CasePriority.P2);
        testCase.setStatus(TestCase.ExecStatus.NOT_RUN);
        testCase.setCreatedAt(LocalDateTime.now());
        testCase.setUpdatedAt(LocalDateTime.now());
        return testCaseRepository.save(testCase);
    }

    public TestCase update(Long id, TestCase changes) {
        validateRequired(changes);
        accessScope.requireProjectOnWrite(changes.getProjectId());
        TestCase testCase = findById(id);
        // 换了项目时重新分配新项目内的序号
        if (!Objects.equals(testCase.getProjectId(), changes.getProjectId())) {
            testCase.setSeq(testCaseRepository.findMaxSeqInProject(changes.getProjectId()) + 1);
        }
        testCase.setProjectId(changes.getProjectId());
        testCase.setTitle(changes.getTitle());
        testCase.setModule(changes.getModule());
        if (changes.getPriority() != null) testCase.setPriority(changes.getPriority());
        testCase.setPrecondition(changes.getPrecondition());
        testCase.setSteps(changes.getSteps());
        testCase.setExpectedResult(changes.getExpectedResult());
        testCase.setDesigner(changes.getDesigner());
        testCase.setUpdatedAt(LocalDateTime.now());
        return testCaseRepository.save(testCase);
    }

    /** 记录一次执行：更新执行状态、实际结果、执行人与执行时间 */
    public TestCase execute(Long id, TestCase.ExecStatus status, String actualResult, String executor) {
        if (status == null) {
            throw new IllegalArgumentException("执行状态不能为空");
        }
        TestCase testCase = findById(id);
        testCase.setStatus(status);
        testCase.setActualResult(actualResult == null || actualResult.isBlank() ? null : actualResult.trim());
        if (executor != null && !executor.isBlank()) {
            testCase.setExecutor(executor.trim());
        }
        testCase.setExecutedAt(LocalDateTime.now());
        testCase.setUpdatedAt(LocalDateTime.now());
        return testCaseRepository.save(testCase);
    }

    public void delete(Long id) {
        TestCase testCase = findById(id); // 含可见性校验
        testCaseRepository.delete(testCase);
    }

    /** 批量导入：逐条创建，失败的行收集错误信息返回，不影响其他行 */
    public Map<String, Object> importBatch(List<TestCase> testCases) {
        if (testCases == null || testCases.isEmpty()) {
            throw new IllegalArgumentException("导入数据不能为空");
        }
        if (testCases.size() > 500) {
            throw new IllegalArgumentException("单次最多导入 500 条");
        }
        int success = 0;
        List<Map<String, Object>> failures = new ArrayList<>();
        for (int i = 0; i < testCases.size(); i++) {
            try {
                create(testCases.get(i));
                success++;
            } catch (Exception e) {
                failures.add(Map.of("row", i + 1, "error", e.getMessage()));
            }
        }
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("total", testCases.size());
        result.put("success", success);
        result.put("failures", failures);
        return result;
    }

    /** 必填字段校验：与前端表单一致，防止直接调接口绕过 */
    private void validateRequired(TestCase testCase) {
        if (testCase.getTitle() == null || testCase.getTitle().isBlank()) {
            throw new IllegalArgumentException("用例标题不能为空");
        }
        testCase.setTitle(testCase.getTitle().trim());
    }

    /** 用例不存在异常 */
    public static class TestCaseNotFoundException extends RuntimeException {
        public TestCaseNotFoundException(Long id) {
            super("测试用例不存在: " + id);
        }
    }
}
