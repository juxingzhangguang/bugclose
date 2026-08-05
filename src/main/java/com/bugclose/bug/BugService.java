package com.bugclose.bug;

import com.bugclose.auth.AccessDeniedException;
import com.bugclose.auth.AccessScope;
import jakarta.persistence.criteria.Predicate;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Bug 业务逻辑：增删改查、状态流转、筛选搜索、统计
 */
@Service
@Transactional
public class BugService {

    private final BugRepository bugRepository;
    private final AccessScope accessScope;

    public BugService(BugRepository bugRepository, AccessScope accessScope) {
        this.bugRepository = bugRepository;
        this.accessScope = accessScope;
    }

    /** 条件查询：项目/状态/严重程度/优先级/处理人可选，关键字模糊匹配标题和描述 */
    @Transactional(readOnly = true)
    public List<Bug> search(Long projectId, Bug.BugStatus status, Bug.Severity severity,
                            Bug.Priority priority, String assignee, String keyword) {
        Specification<Bug> spec = (root, query, cb) -> {
            List<Predicate> predicates = new ArrayList<>();
            // 数据隔离：普通用户只能看到绑定项目内的 Bug（自动排除未关联项目的 Bug）
            if (!accessScope.isAllAccess()) {
                predicates.add(root.get("projectId").in(accessScope.visibleProjectIds()));
            }
            if (projectId != null) {
                predicates.add(cb.equal(root.get("projectId"), projectId));
            }
            if (status != null) {
                predicates.add(cb.equal(root.get("status"), status));
            }
            if (severity != null) {
                predicates.add(cb.equal(root.get("severity"), severity));
            }
            if (priority != null) {
                predicates.add(cb.equal(root.get("priority"), priority));
            }
            if (assignee != null && !assignee.isBlank()) {
                predicates.add(cb.equal(root.get("assignee"), assignee.trim()));
            }
            if (keyword != null && !keyword.isBlank()) {
                String like = "%" + keyword.trim().toLowerCase() + "%";
                predicates.add(cb.or(
                        cb.like(cb.lower(root.get("title")), like),
                        cb.like(cb.lower(root.get("description")), like)));
            }
            return cb.and(predicates.toArray(new Predicate[0]));
        };
        return bugRepository.findAll(spec, Sort.by(Sort.Direction.DESC, "createdAt"));
    }

    @Transactional(readOnly = true)
    public Bug findById(Long id) {
        Bug bug = bugRepository.findById(id)
                .orElseThrow(() -> new BugNotFoundException(id));
        accessScope.requireVisible(bug.getProjectId());
        return bug;
    }

    public Bug create(Bug bug) {
        validateRequired(bug);
        accessScope.requireProjectOnWrite(bug.getProjectId());
        bug.setId(null);
        bug.setSeq(bugRepository.findMaxSeqInProject(bug.getProjectId()) + 1);
        bug.setCreatedAt(LocalDateTime.now());
        bug.setUpdatedAt(LocalDateTime.now());
        if (bug.getStatus() == null) {
            bug.setStatus(Bug.BugStatus.NEW);
        }
        return bugRepository.save(bug);
    }

    public Bug update(Long id, Bug changes) {
        validateRequired(changes);
        accessScope.requireProjectOnWrite(changes.getProjectId());
        Bug bug = findById(id);
        // 换了项目时重新分配新项目内的序号
        if (!java.util.Objects.equals(bug.getProjectId(), changes.getProjectId())) {
            bug.setSeq(bugRepository.findMaxSeqInProject(changes.getProjectId()) + 1);
        }
        bug.setProjectId(changes.getProjectId());
        bug.setTitle(changes.getTitle());
        bug.setDescription(changes.getDescription());
        bug.setSeverity(changes.getSeverity());
        bug.setPriority(changes.getPriority());
        bug.setAssignee(changes.getAssignee());
        bug.setEnvironment(changes.getEnvironment());
        bug.setModule(changes.getModule());
        bug.setReporter(changes.getReporter());
        bug.setImages(changes.getImages());
        bug.setUpdatedAt(LocalDateTime.now());
        return bugRepository.save(bug);
    }

    /** 状态流转：NEW → IN_PROGRESS → RESOLVED → CLOSED，可同时指派处理人 */
    public Bug transition(Long id, Bug.BugStatus targetStatus, String assignee) {
        Bug bug = findById(id);
        if (!isValidTransition(bug.getStatus(), targetStatus)) {
            throw new IllegalStateException(
                    "不允许从 " + bug.getStatus() + " 流转到 " + targetStatus);
        }
        bug.setStatus(targetStatus);
        if (assignee != null && !assignee.isBlank()) {
            bug.setAssignee(assignee.trim());
        }
        bug.setUpdatedAt(LocalDateTime.now());
        return bugRepository.save(bug);
    }

    public void delete(Long id) {
        Bug bug = findById(id); // 含可见性校验
        bugRepository.delete(bug);
    }

    /** 统计：按状态、严重程度、处理人分组计数（仅统计当前用户可见项目的 Bug） */
    @Transactional(readOnly = true)
    public Map<String, Object> statistics() {
        List<Bug> all = bugRepository.findAll().stream()
                .filter(b -> {
                    try {
                        accessScope.requireVisible(b.getProjectId());
                        return true;
                    } catch (AccessDeniedException e) {
                        return false;
                    }
                })
                .toList();

        Map<Bug.BugStatus, Long> byStatus = new EnumMap<>(Bug.BugStatus.class);
        for (Bug.BugStatus s : Bug.BugStatus.values()) {
            byStatus.put(s, 0L);
        }
        Map<Bug.Severity, Long> bySeverity = new EnumMap<>(Bug.Severity.class);
        for (Bug.Severity s : Bug.Severity.values()) {
            bySeverity.put(s, 0L);
        }
        Map<String, Long> byAssignee = new LinkedHashMap<>();

        for (Bug bug : all) {
            byStatus.merge(bug.getStatus(), 1L, Long::sum);
            bySeverity.merge(bug.getSeverity(), 1L, Long::sum);
            String assignee = (bug.getAssignee() == null || bug.getAssignee().isBlank())
                    ? "未指派" : bug.getAssignee();
            byAssignee.merge(assignee, 1L, Long::sum);
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("total", all.size());
        result.put("byStatus", byStatus);
        result.put("bySeverity", bySeverity);
        result.put("byAssignee", byAssignee);
        return result;
    }

    /** 必填字段校验：与前端表单一致，防止直接调接口绕过 */
    private void validateRequired(Bug bug) {
        if (bug.getTitle() == null || bug.getTitle().isBlank()) {
            throw new IllegalStateException("标题不能为空");
        }
        if (bug.getEnvironment() == null || bug.getEnvironment().isBlank()) {
            throw new IllegalStateException("影响环境不能为空");
        }
        if (bug.getModule() == null || bug.getModule().isBlank()) {
            throw new IllegalStateException("影响模块不能为空");
        }
        bug.setTitle(bug.getTitle().trim());
        bug.setEnvironment(bug.getEnvironment().trim());
        bug.setModule(bug.getModule().trim());
    }

    /** 合法流转规则：允许相邻推进、驳回重开（RESOLVED/CLOSED → IN_PROGRESS） */
    private boolean isValidTransition(Bug.BugStatus from, Bug.BugStatus to) {
        if (from == to) {
            return false;
        }
        return switch (from) {
            case NEW -> to == Bug.BugStatus.IN_PROGRESS || to == Bug.BugStatus.CLOSED;
            case IN_PROGRESS -> to == Bug.BugStatus.RESOLVED || to == Bug.BugStatus.CLOSED;
            case RESOLVED -> to == Bug.BugStatus.CLOSED || to == Bug.BugStatus.IN_PROGRESS;
            case CLOSED -> to == Bug.BugStatus.IN_PROGRESS;
        };
    }

    /** Bug 不存在异常 */
    public static class BugNotFoundException extends RuntimeException {
        public BugNotFoundException(Long id) {
            super("Bug 不存在: id=" + id);
        }
    }
}
