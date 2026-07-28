package com.bugclose.bug;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

/**
 * Bug 数据访问层，支持动态条件查询
 */
public interface BugRepository extends JpaRepository<Bug, Long>, JpaSpecificationExecutor<Bug> {
}
