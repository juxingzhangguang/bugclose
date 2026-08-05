package com.bugclose.project;

import com.bugclose.auth.AccessScope;
import com.bugclose.auth.AuthContext;
import com.bugclose.bug.BugRepository;
import com.bugclose.requirement.RequirementRepository;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Set;

/**
 * 项目业务逻辑：增删改查，删除前校验是否仍有关联 Bug。
 * 项目 CRUD 为管理员专用；列表按当前用户可见范围过滤（普通用户只看到绑定项目）。
 */
@Service
@Transactional
public class ProjectService {

    private final ProjectRepository projectRepository;
    private final BugRepository bugRepository;
    private final RequirementRepository requirementRepository;
    private final AccessScope accessScope;

    public ProjectService(ProjectRepository projectRepository, BugRepository bugRepository,
                          RequirementRepository requirementRepository, AccessScope accessScope) {
        this.projectRepository = projectRepository;
        this.bugRepository = bugRepository;
        this.requirementRepository = requirementRepository;
        this.accessScope = accessScope;
    }

    /** 项目视图：附带关联 Bug 数量 */
    public record ProjectView(Long id, String name, String code, String description,
                              LocalDateTime createdAt, long bugCount) {
    }

    @Transactional(readOnly = true)
    public List<ProjectView> listWithBugCount() {
        Set<Long> visible = accessScope.visibleProjectIds();
        return projectRepository.findAll(Sort.by(Sort.Direction.ASC, "createdAt")).stream()
                .filter(p -> visible == null || visible.contains(p.getId()))
                .map(p -> new ProjectView(p.getId(), p.getName(), p.getCode(), p.getDescription(),
                        p.getCreatedAt(), bugRepository.countByProjectId(p.getId())))
                .toList();
    }

    @Transactional(readOnly = true)
    public Project findById(Long id) {
        Project project = projectRepository.findById(id)
                .orElseThrow(() -> new ProjectNotFoundException(id));
        accessScope.requireVisible(id);
        return project;
    }

    public Project create(Project project) {
        AuthContext.requireAdmin();
        if (project.getName() == null || project.getName().isBlank()) {
            throw new IllegalStateException("项目名称不能为空");
        }
        String name = project.getName().trim();
        if (projectRepository.existsByName(name)) {
            throw new IllegalStateException("项目名称已存在: " + name);
        }
        String code = normalizeCode(project.getCode());
        if (code != null && projectRepository.existsByCode(code)) {
            throw new IllegalStateException("项目编号已存在: " + code);
        }
        project.setId(null);
        project.setName(name);
        project.setCode(code);
        project.setCreatedAt(LocalDateTime.now());
        return projectRepository.save(project);
    }

    public Project update(Long id, Project changes) {
        AuthContext.requireAdmin();
        Project project = findById(id);
        if (changes.getName() == null || changes.getName().isBlank()) {
            throw new IllegalStateException("项目名称不能为空");
        }
        String name = changes.getName().trim();
        if (projectRepository.existsByNameAndIdNot(name, id)) {
            throw new IllegalStateException("项目名称已存在: " + name);
        }
        String code = normalizeCode(changes.getCode());
        if (code != null && projectRepository.existsByCodeAndIdNot(code, id)) {
            throw new IllegalStateException("项目编号已存在: " + code);
        }
        project.setName(name);
        project.setCode(code);
        project.setDescription(changes.getDescription());
        return projectRepository.save(project);
    }

    /** 编号规范化：去首尾空格并转大写，空白视为未设置 */
    private String normalizeCode(String code) {
        if (code == null || code.isBlank()) {
            return null;
        }
        return code.trim().toUpperCase();
    }

    public void delete(Long id) {
        AuthContext.requireAdmin();
        Project project = findById(id);
        long bugCount = bugRepository.countByProjectId(id);
        if (bugCount > 0) {
            throw new IllegalStateException(
                    "项目「" + project.getName() + "」下还有 " + bugCount + " 个 Bug，请先处理后再删除");
        }
        long reqCount = requirementRepository.countByProjectId(id);
        if (reqCount > 0) {
            throw new IllegalStateException(
                    "项目「" + project.getName() + "」下还有 " + reqCount + " 个需求，请先处理后再删除");
        }
        projectRepository.deleteById(id);
    }

    /** 项目不存在异常 */
    public static class ProjectNotFoundException extends RuntimeException {
        public ProjectNotFoundException(Long id) {
            super("项目不存在: id=" + id);
        }
    }
}
