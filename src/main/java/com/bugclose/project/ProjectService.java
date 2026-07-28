package com.bugclose.project;

import com.bugclose.bug.BugRepository;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 项目业务逻辑：增删改查，删除前校验是否仍有关联 Bug
 */
@Service
@Transactional
public class ProjectService {

    private final ProjectRepository projectRepository;
    private final BugRepository bugRepository;

    public ProjectService(ProjectRepository projectRepository, BugRepository bugRepository) {
        this.projectRepository = projectRepository;
        this.bugRepository = bugRepository;
    }

    /** 项目视图：附带关联 Bug 数量 */
    public record ProjectView(Long id, String name, String code, String description,
                              LocalDateTime createdAt, long bugCount) {
    }

    @Transactional(readOnly = true)
    public List<ProjectView> listWithBugCount() {
        return projectRepository.findAll(Sort.by(Sort.Direction.ASC, "createdAt")).stream()
                .map(p -> new ProjectView(p.getId(), p.getName(), p.getCode(), p.getDescription(),
                        p.getCreatedAt(), bugRepository.countByProjectId(p.getId())))
                .toList();
    }

    @Transactional(readOnly = true)
    public Project findById(Long id) {
        return projectRepository.findById(id)
                .orElseThrow(() -> new ProjectNotFoundException(id));
    }

    public Project create(Project project) {
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
        Project project = findById(id);
        long bugCount = bugRepository.countByProjectId(id);
        if (bugCount > 0) {
            throw new IllegalStateException(
                    "项目「" + project.getName() + "」下还有 " + bugCount + " 个 Bug，请先处理后再删除");
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
