package com.bugclose.testcase;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

/**
 * 测试用例仓库
 */
public interface TestCaseRepository extends JpaRepository<TestCase, Long>, JpaSpecificationExecutor<TestCase> {

    /** 查询项目内当前最大序号（未关联项目的用例自成一套序号） */
    @Query("select coalesce(max(t.seq), 0) from TestCase t "
            + "where (:projectId is null and t.projectId is null) or t.projectId = :projectId")
    long findMaxSeqInProject(@Param("projectId") Long projectId);
}
