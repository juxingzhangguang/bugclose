package com.bugclose.bug;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

/**
 * Bug 数据访问层，支持动态条件查询
 */
public interface BugRepository extends JpaRepository<Bug, Long>, JpaSpecificationExecutor<Bug> {

    long countByProjectId(Long projectId);

    /** 查询项目内当前最大序号（projectId 为 null 时统计未关联项目的 Bug） */
    @Query("select coalesce(max(b.seq), 0) from Bug b "
            + "where (:projectId is null and b.projectId is null) or b.projectId = :projectId")
    long findMaxSeqInProject(@Param("projectId") Long projectId);
}
