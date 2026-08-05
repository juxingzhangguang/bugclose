package com.bugclose.requirement;

import com.bugclose.auth.AccessScope;
import com.bugclose.project.ProjectRepository;
import jakarta.persistence.criteria.Predicate;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

/**
 * 需求业务逻辑
 */
@Service
@Transactional
public class RequirementService {

    private final RequirementRepository requirementRepository;
    private final ProjectRepository projectRepository;
    private final AccessScope accessScope;

    public RequirementService(RequirementRepository requirementRepository, ProjectRepository projectRepository,
                              AccessScope accessScope) {
        this.requirementRepository = requirementRepository;
        this.projectRepository = projectRepository;
        this.accessScope = accessScope;
    }

    /** 条件查询：项目 / 状态 / 优先级 / 所属期 / 关键字（标题、模块） */
    @Transactional(readOnly = true)
    public List<Requirement> search(Long projectId, Requirement.ReqStatus status,
                                     Requirement.ReqPriority priority, String period, String keyword) {
        Specification<Requirement> spec = (root, query, cb) -> {
            List<Predicate> predicates = new ArrayList<>();
            if (!accessScope.isAllAccess()) {
                predicates.add(root.get("projectId").in(accessScope.visibleProjectIds()));
            }
            if (projectId != null) predicates.add(cb.equal(root.get("projectId"), projectId));
            if (status != null) predicates.add(cb.equal(root.get("status"), status));
            if (priority != null) predicates.add(cb.equal(root.get("priority"), priority));
            if (period != null && !period.isBlank()) predicates.add(cb.equal(root.get("period"), period.trim()));
            if (keyword != null && !keyword.isBlank()) {
                String like = "%" + keyword.trim().toLowerCase() + "%";
                predicates.add(cb.or(
                        cb.like(cb.lower(root.get("title")), like),
                        cb.like(cb.lower(root.get("module")), like)));
            }
            return cb.and(predicates.toArray(new Predicate[0]));
        };
        return requirementRepository.findAll(spec, Sort.by("id"));
    }

    @Transactional(readOnly = true)
    public Requirement findById(Long id) {
        Requirement req = requirementRepository.findById(id)
                .orElseThrow(() -> new RequirementNotFoundException(id));
        accessScope.requireVisible(req.getProjectId());
        return req;
    }

    public Requirement create(Requirement req) {
        validateRequired(req);
        if (req.getProjectId() != null && !projectRepository.existsById(req.getProjectId())) {
            throw new IllegalArgumentException("关联项目不存在");
        }
        accessScope.requireProjectOnWrite(req.getProjectId());
        req.setId(null);
        req.setSeq(requirementRepository.findMaxSeqInProject(req.getProjectId()) + 1);
        if (req.getPriority() == null) req.setPriority(Requirement.ReqPriority.P2);
        if (req.getStatus() == null) req.setStatus(Requirement.ReqStatus.DRAFT);
        req.setCreatedAt(LocalDateTime.now());
        req.setUpdatedAt(LocalDateTime.now());
        return requirementRepository.save(req);
    }

    public Requirement update(Long id, Requirement changes) {
        validateRequired(changes);
        if (changes.getProjectId() != null && !projectRepository.existsById(changes.getProjectId())) {
            throw new IllegalArgumentException("关联项目不存在");
        }
        accessScope.requireProjectOnWrite(changes.getProjectId());
        Requirement req = findById(id);
        // 换了项目时重新分配新项目内的序号
        if (!Objects.equals(req.getProjectId(), changes.getProjectId())) {
            req.setSeq(requirementRepository.findMaxSeqInProject(changes.getProjectId()) + 1);
        }
        req.setProjectId(changes.getProjectId());
        req.setTitle(changes.getTitle());
        req.setDescription(changes.getDescription());
        req.setPeriod(changes.getPeriod());
        req.setModule(changes.getModule());
        if (changes.getPriority() != null) req.setPriority(changes.getPriority());
        if (changes.getStatus() != null) req.setStatus(changes.getStatus());
        req.setProposer(changes.getProposer());
        req.setAssignee(changes.getAssignee());
        req.setUpdatedAt(LocalDateTime.now());
        return requirementRepository.save(req);
    }

    public void delete(Long id) {
        Requirement req = findById(id); // 含可见性校验
        requirementRepository.delete(req);
    }

    /** 必填字段校验：与前端表单一致，防止直接调接口绕过 */
    private void validateRequired(Requirement req) {
        if (req.getTitle() == null || req.getTitle().isBlank()) {
            throw new IllegalArgumentException("需求标题不能为空");
        }
        req.setTitle(req.getTitle().trim());
    }

    /** 需求不存在异常 */
    public static class RequirementNotFoundException extends RuntimeException {
        public RequirementNotFoundException(Long id) {
            super("需求不存在: " + id);
        }
    }
}
