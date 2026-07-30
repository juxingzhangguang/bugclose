package com.bugclose.testcase;

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
 * 测试用例实体
 */
@Entity
@Table(name = "test_cases")
public class TestCase {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** 项目内序号（展示编号用，如 MALL-TC1），全局 id 仅作内部主键 */
    @Column(nullable = false)
    private Long seq;

    /** 所属项目 ID（可空，不建外键关联） */
    private Long projectId;

    /** 用例标题 */
    @Column(nullable = false, length = 200)
    private String title;

    /** 所属模块（自定义输入；列名避开 SQL 关键字 module） */
    @Column(name = "module_name", length = 100)
    private String module;

    /** 用例优先级：P0 冒烟 > P1 核心 > P2 一般 > P3 边缘 */
    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 10)
    private CasePriority priority = CasePriority.P2;

    /** 前置条件 */
    @Column(length = 1000)
    private String precondition;

    /** 测试步骤 */
    @Lob
    private String steps;

    /** 预期结果 */
    @Lob
    private String expectedResult;

    /** 执行状态 */
    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private ExecStatus status = ExecStatus.NOT_RUN;

    /** 最近一次执行的实际结果 / 备注 */
    @Lob
    private String actualResult;

    /** 最近执行人 */
    @Column(length = 50)
    private String executor;

    /** 最近执行时间 */
    private LocalDateTime executedAt;

    /** 编写人 */
    @Column(length = 50)
    private String designer;

    @Column(updatable = false)
    private LocalDateTime createdAt;

    private LocalDateTime updatedAt;

    /** 用例优先级 */
    public enum CasePriority { P0, P1, P2, P3 }

    /** 执行状态：未执行 / 通过 / 失败 / 阻塞 */
    public enum ExecStatus { NOT_RUN, PASS, FAIL, BLOCKED }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Long getSeq() { return seq; }
    public void setSeq(Long seq) { this.seq = seq; }
    public Long getProjectId() { return projectId; }
    public void setProjectId(Long projectId) { this.projectId = projectId; }
    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }
    public String getModule() { return module; }
    public void setModule(String module) { this.module = module; }
    public CasePriority getPriority() { return priority; }
    public void setPriority(CasePriority priority) { this.priority = priority; }
    public String getPrecondition() { return precondition; }
    public void setPrecondition(String precondition) { this.precondition = precondition; }
    public String getSteps() { return steps; }
    public void setSteps(String steps) { this.steps = steps; }
    public String getExpectedResult() { return expectedResult; }
    public void setExpectedResult(String expectedResult) { this.expectedResult = expectedResult; }
    public ExecStatus getStatus() { return status; }
    public void setStatus(ExecStatus status) { this.status = status; }
    public String getActualResult() { return actualResult; }
    public void setActualResult(String actualResult) { this.actualResult = actualResult; }
    public String getExecutor() { return executor; }
    public void setExecutor(String executor) { this.executor = executor; }
    public LocalDateTime getExecutedAt() { return executedAt; }
    public void setExecutedAt(LocalDateTime executedAt) { this.executedAt = executedAt; }
    public String getDesigner() { return designer; }
    public void setDesigner(String designer) { this.designer = designer; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
    public LocalDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(LocalDateTime updatedAt) { this.updatedAt = updatedAt; }
}
