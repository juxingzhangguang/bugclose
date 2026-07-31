package com.bugclose.requirement;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Lob;
import jakarta.persistence.Table;

import java.time.LocalDateTime;

/**
 * 需求实体
 */
@Entity
@Table(name = "requirements")
public class Requirement {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** 项目内序号（展示编号用），全局 id 仅作内部主键 */
    @Column(nullable = false)
    private Long seq;

    /** 所属项目 ID（可空，不建外键关联） */
    private Long projectId;

    /** 需求标题 */
    @Column(nullable = false, length = 200)
    private String title;

    /** 详细描述 */
    @Lob
    @Column(length = 4000)
    private String description;

    /** 所属期（如"一期"、"二期"），可空 */
    @Column(length = 50)
    private String period;

    /** 所属模块（自定义输入；列名避开 SQL 关键字 module） */
    @Column(name = "module_name", length = 100)
    private String module;

    /** 需求优先级：P0 紧急 > P1 高 > P2 中 > P3 低 */
    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 10)
    private ReqPriority priority = ReqPriority.P2;

    /** 需求状态 */
    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private ReqStatus status = ReqStatus.DRAFT;

    /** 提出人 */
    @Column(length = 50)
    private String proposer;

    /** 负责人 */
    @Column(length = 50)
    private String assignee;

    @Column(updatable = false)
    private LocalDateTime createdAt;

    private LocalDateTime updatedAt;

    /** 需求优先级 */
    public enum ReqPriority { P0, P1, P2, P3 }

    /** 需求状态：草稿 / 评审中 / 已通过 / 进行中 / 已完成 / 已拒绝 */
    public enum ReqStatus { DRAFT, REVIEWING, APPROVED, IN_PROGRESS, COMPLETED, REJECTED }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Long getSeq() { return seq; }
    public void setSeq(Long seq) { this.seq = seq; }
    public Long getProjectId() { return projectId; }
    public void setProjectId(Long projectId) { this.projectId = projectId; }
    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    public String getPeriod() { return period; }
    public void setPeriod(String period) { this.period = period; }
    public String getModule() { return module; }
    public void setModule(String module) { this.module = module; }
    public ReqPriority getPriority() { return priority; }
    public void setPriority(ReqPriority priority) { this.priority = priority; }
    public ReqStatus getStatus() { return status; }
    public void setStatus(ReqStatus status) { this.status = status; }
    public String getProposer() { return proposer; }
    public void setProposer(String proposer) { this.proposer = proposer; }
    public String getAssignee() { return assignee; }
    public void setAssignee(String assignee) { this.assignee = assignee; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
    public LocalDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(LocalDateTime updatedAt) { this.updatedAt = updatedAt; }
}
